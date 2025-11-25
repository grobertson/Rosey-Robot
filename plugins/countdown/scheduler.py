"""
plugins/countdown/scheduler.py

Asyncio-based countdown scheduler.

Uses a single polling loop to check all active countdowns rather than
creating individual tasks per countdown. This is more efficient and
easier to manage.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Awaitable


class CountdownScheduler:
    """
    Manages countdown timers using asyncio.
    
    Uses a single task that checks countdowns at regular intervals
    rather than creating one task per countdown. This approach is:
    - More memory efficient
    - Easier to stop cleanly
    - Simpler to debug
    
    Args:
        check_interval: Seconds between checks (default: 30).
        on_complete: Async callback when countdown completes.
        on_check: Async callback for each countdown during checks (for alerts).
    """
    
    def __init__(
        self,
        check_interval: float = 30.0,
        on_complete: Optional[Callable[[str], Awaitable[None]]] = None,
        on_check: Optional[Callable[[str, timedelta], Awaitable[None]]] = None
    ):
        """
        Initialize the scheduler.
        
        Args:
            check_interval: Seconds between scheduler checks.
            on_complete: Async callback called with countdown_id when complete.
            on_check: Async callback called with (countdown_id, remaining) each check.
        """
        self.check_interval = check_interval
        self.on_complete = on_complete
        self.on_check = on_check
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._pending: Dict[str, datetime] = {}  # countdown_id -> target_time
        self.logger = logging.getLogger(f"{__name__}.scheduler")
    
    async def start(self) -> None:
        """
        Start the scheduler loop.
        
        Creates a background task that periodically checks for
        completed countdowns.
        """
        if self.running:
            self.logger.warning("Scheduler already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._check_loop())
        self.logger.info(
            f"Scheduler started (interval: {self.check_interval}s, "
            f"tracking: {len(self._pending)} countdowns)"
        )
    
    async def stop(self) -> None:
        """
        Stop the scheduler loop gracefully.
        
        Cancels the background task and waits for it to finish.
        Does not clear pending countdowns (they persist in storage).
        """
        if not self.running:
            return
        
        self.running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        self.logger.info("Scheduler stopped")
    
    def schedule(self, countdown_id: str, target_time: datetime) -> None:
        """
        Add a countdown to track.
        
        Args:
            countdown_id: Unique identifier (usually "channel:name").
            target_time: When the countdown should fire.
        """
        self._pending[countdown_id] = target_time
        self.logger.debug(f"Scheduled countdown: {countdown_id} at {target_time}")
    
    def cancel(self, countdown_id: str) -> bool:
        """
        Remove a countdown from tracking.
        
        Args:
            countdown_id: The countdown to cancel.
            
        Returns:
            True if countdown was found and removed, False otherwise.
        """
        if countdown_id in self._pending:
            del self._pending[countdown_id]
            self.logger.debug(f"Cancelled countdown: {countdown_id}")
            return True
        return False
    
    def is_scheduled(self, countdown_id: str) -> bool:
        """Check if a countdown is being tracked."""
        return countdown_id in self._pending
    
    @property
    def pending_count(self) -> int:
        """Number of countdowns being tracked."""
        return len(self._pending)
    
    def get_pending_ids(self) -> List[str]:
        """Get list of all pending countdown IDs."""
        return list(self._pending.keys())
    
    async def _check_loop(self) -> None:
        """
        Main loop that checks for completed countdowns.
        
        Runs until stopped, checking all pending countdowns each interval.
        When a countdown completes, calls the on_complete callback.
        For pending countdowns, calls on_check for alert processing.
        """
        self.logger.debug("Check loop started")
        
        while self.running:
            try:
                now = datetime.now(timezone.utc)
                
                # Find completed countdowns
                completed = self._get_completed()
                
                # Process non-completed countdowns for alerts
                if self.on_check:
                    for countdown_id, target_time in self._pending.items():
                        if countdown_id in completed:
                            continue  # Skip completed ones
                        
                        # Handle both aware and naive datetimes
                        if target_time.tzinfo is None:
                            target_time = target_time.replace(tzinfo=timezone.utc)
                        
                        remaining = target_time - now
                        if remaining.total_seconds() > 0:
                            try:
                                await self.on_check(countdown_id, remaining)
                            except Exception as e:
                                self.logger.error(
                                    f"Error in check callback for {countdown_id}: {e}"
                                )
                
                # Process each completed countdown
                for countdown_id in completed:
                    # Remove from pending
                    del self._pending[countdown_id]
                    
                    # Call completion callback
                    if self.on_complete:
                        try:
                            await self.on_complete(countdown_id)
                        except Exception as e:
                            self.logger.exception(
                                f"Error in completion callback for {countdown_id}: {e}"
                            )
                
                # Wait for next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                self.logger.debug("Check loop cancelled")
                raise
            except Exception as e:
                self.logger.exception(f"Error in check loop: {e}")
                # Continue running despite errors
                await asyncio.sleep(self.check_interval)
        
        self.logger.debug("Check loop ended")
    
    def _get_completed(self) -> List[str]:
        """
        Get list of countdown IDs that have completed.
        
        Returns:
            List of countdown_ids whose target_time has passed.
        """
        now = datetime.now(timezone.utc)
        completed = []
        
        for countdown_id, target_time in self._pending.items():
            # Handle both aware and naive datetimes
            if target_time.tzinfo is None:
                target_time = target_time.replace(tzinfo=timezone.utc)
            
            if now >= target_time:
                completed.append(countdown_id)
        
        return completed
