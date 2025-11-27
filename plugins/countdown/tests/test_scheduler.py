"""
tests/test_scheduler.py

Unit tests for the CountdownScheduler.

Tests cover:
- Scheduler lifecycle (start/stop)
- Adding/removing countdowns
- Completion callback triggering
- Edge cases and error handling
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler import CountdownScheduler


# =============================================================================
# Scheduler Lifecycle Tests
# =============================================================================

class TestSchedulerLifecycle:
    """Tests for scheduler start/stop lifecycle."""
    
    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """start() creates a running task."""
        scheduler = CountdownScheduler(check_interval=1.0)
        
        await scheduler.start()
        
        assert scheduler.running is True
        assert scheduler._task is not None
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """stop() cancels the running task."""
        scheduler = CountdownScheduler(check_interval=1.0)
        
        await scheduler.start()
        await scheduler.stop()
        
        assert scheduler.running is False
        assert scheduler._task is None
    
    @pytest.mark.asyncio
    async def test_double_start_warns(self):
        """Starting twice doesn't create duplicate tasks."""
        scheduler = CountdownScheduler(check_interval=1.0)
        
        await scheduler.start()
        task1 = scheduler._task
        
        await scheduler.start()  # Second start
        task2 = scheduler._task
        
        assert task1 is task2  # Same task
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """stop() without start() doesn't error."""
        scheduler = CountdownScheduler(check_interval=1.0)
        
        # Should not raise
        await scheduler.stop()


# =============================================================================
# Schedule/Cancel Tests
# =============================================================================

class TestScheduleCancel:
    """Tests for scheduling and canceling countdowns."""
    
    def test_schedule_adds_countdown(self):
        """schedule() adds countdown to pending."""
        scheduler = CountdownScheduler()
        target = datetime.now(timezone.utc) + timedelta(hours=1)
        
        scheduler.schedule("test:countdown", target)
        
        assert "test:countdown" in scheduler._pending
        assert scheduler._pending["test:countdown"] == target
    
    def test_cancel_removes_countdown(self):
        """cancel() removes countdown from pending."""
        scheduler = CountdownScheduler()
        target = datetime.now(timezone.utc) + timedelta(hours=1)
        
        scheduler.schedule("test:countdown", target)
        result = scheduler.cancel("test:countdown")
        
        assert result is True
        assert "test:countdown" not in scheduler._pending
    
    def test_cancel_nonexistent_returns_false(self):
        """cancel() returns False for nonexistent countdown."""
        scheduler = CountdownScheduler()
        
        result = scheduler.cancel("nonexistent")
        
        assert result is False
    
    def test_is_scheduled(self):
        """is_scheduled() returns correct status."""
        scheduler = CountdownScheduler()
        target = datetime.now(timezone.utc) + timedelta(hours=1)
        
        assert scheduler.is_scheduled("test") is False
        
        scheduler.schedule("test", target)
        assert scheduler.is_scheduled("test") is True
    
    def test_pending_count(self):
        """pending_count returns correct number."""
        scheduler = CountdownScheduler()
        
        assert scheduler.pending_count == 0
        
        scheduler.schedule("a", datetime.now(timezone.utc))
        scheduler.schedule("b", datetime.now(timezone.utc))
        
        assert scheduler.pending_count == 2
    
    def test_get_pending_ids(self):
        """get_pending_ids returns all IDs."""
        scheduler = CountdownScheduler()
        
        scheduler.schedule("a", datetime.now(timezone.utc))
        scheduler.schedule("b", datetime.now(timezone.utc))
        
        ids = scheduler.get_pending_ids()
        assert set(ids) == {"a", "b"}


# =============================================================================
# Completion Detection Tests
# =============================================================================

class TestCompletionDetection:
    """Tests for countdown completion detection."""
    
    def test_get_completed_finds_expired(self):
        """_get_completed finds expired countdowns."""
        scheduler = CountdownScheduler()
        
        # Add one expired, one future
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        
        scheduler.schedule("expired", past)
        scheduler.schedule("future", future)
        
        completed = scheduler._get_completed()
        
        assert "expired" in completed
        assert "future" not in completed
    
    def test_get_completed_handles_naive_datetime(self):
        """_get_completed handles naive datetimes."""
        scheduler = CountdownScheduler()
        
        # Naive datetime (no timezone) - use datetime.now(timezone.utc).replace(tzinfo=None)
        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        scheduler.schedule("expired", past)
        
        completed = scheduler._get_completed()
        assert "expired" in completed
    
    @pytest.mark.asyncio
    async def test_completion_callback_called(self):
        """Completion callback is called when countdown expires."""
        callback = AsyncMock()
        scheduler = CountdownScheduler(check_interval=0.1, on_complete=callback)
        
        # Add expired countdown
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        scheduler.schedule("test", past)
        
        await scheduler.start()
        
        # Wait for check loop to run
        await asyncio.sleep(0.2)
        
        await scheduler.stop()
        
        # Callback should have been called
        callback.assert_called_once_with("test")
    
    @pytest.mark.asyncio
    async def test_completed_removed_from_pending(self):
        """Completed countdown is removed from pending."""
        callback = AsyncMock()
        scheduler = CountdownScheduler(check_interval=0.1, on_complete=callback)
        
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        scheduler.schedule("test", past)
        
        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()
        
        assert "test" not in scheduler._pending


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in scheduler."""
    
    @pytest.mark.asyncio
    async def test_callback_error_doesnt_crash(self):
        """Error in callback doesn't crash scheduler."""
        async def bad_callback(countdown_id):
            raise Exception("Test error")
        
        scheduler = CountdownScheduler(check_interval=0.1, on_complete=bad_callback)
        
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        scheduler.schedule("test", past)
        
        await scheduler.start()
        await asyncio.sleep(0.2)
        
        # Scheduler should still be running despite error
        assert scheduler.running is True
        
        await scheduler.stop()
    
    @pytest.mark.asyncio
    async def test_scheduler_continues_after_callback_error(self):
        """Scheduler continues checking after callback error."""
        call_count = 0
        
        async def counting_callback(countdown_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First call error")
        
        scheduler = CountdownScheduler(check_interval=0.1, on_complete=counting_callback)
        
        # Add two expired countdowns
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        scheduler.schedule("first", past)
        scheduler.schedule("second", past)
        
        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()
        
        # Both should have been processed
        assert call_count == 2
