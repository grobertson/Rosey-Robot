"""
Unit tests for SQL Rate Limiter.

Tests the SQLRateLimiter class including sliding window algorithm,
per-plugin quotas, and RateLimitError handling.
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from lib.storage.sql_rate_limit import RateLimitError, RateLimitStatus, SQLRateLimiter


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_init_with_retry_after(self):
        """Test error includes retry_after_ms."""
        error = RateLimitError("Rate limit exceeded", retry_after_ms=5000)

        assert error.retry_after_ms == 5000
        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert "Rate limit exceeded" in str(error)

    def test_init_with_details(self):
        """Test error includes details dict."""
        error = RateLimitError(
            "Limit exceeded",
            retry_after_ms=1000,
            details={"plugin": "test", "limit": 100},
        )

        assert error.details["plugin"] == "test"
        assert error.details["limit"] == 100
        assert error.details["retry_after_ms"] == 1000


class TestSQLRateLimiter:
    """Tests for SQLRateLimiter class."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter with small window for testing."""
        return SQLRateLimiter(default_limit=5, window_seconds=1)

    # Initialization tests

    def test_init_default_values(self):
        """Test default initialization."""
        limiter = SQLRateLimiter()

        assert limiter.default_limit == 100
        assert limiter.window_seconds == 60

    def test_init_custom_values(self):
        """Test custom initialization."""
        limiter = SQLRateLimiter(default_limit=50, window_seconds=30)

        assert limiter.default_limit == 50
        assert limiter.window_seconds == 30

    def test_init_invalid_limit_raises(self):
        """Test invalid limit raises ValueError."""
        with pytest.raises(ValueError, match="default_limit must be positive"):
            SQLRateLimiter(default_limit=0)

        with pytest.raises(ValueError, match="default_limit must be positive"):
            SQLRateLimiter(default_limit=-1)

    def test_init_invalid_window_raises(self):
        """Test invalid window raises ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be positive"):
            SQLRateLimiter(window_seconds=0)

    # Limit configuration tests

    def test_set_limit_custom(self, limiter):
        """Test setting custom limit for plugin."""
        limiter.set_limit("high-priority", 100)

        assert limiter.get_limit("high-priority") == 100
        assert limiter.get_limit("other") == 5  # Default

    def test_set_limit_zero_blocks_all(self, limiter):
        """Test setting limit to 0 blocks all requests."""
        limiter.set_limit("blocked-plugin", 0)

        assert limiter.get_limit("blocked-plugin") == 0

    def test_set_limit_negative_raises(self, limiter):
        """Test negative limit raises ValueError."""
        with pytest.raises(ValueError, match="limit cannot be negative"):
            limiter.set_limit("plugin", -1)

    def test_remove_limit_reverts_to_default(self, limiter):
        """Test removing custom limit reverts to default."""
        limiter.set_limit("plugin", 100)
        assert limiter.get_limit("plugin") == 100

        limiter.remove_limit("plugin")
        assert limiter.get_limit("plugin") == 5  # Default

    # Check tests

    @pytest.mark.asyncio
    async def test_check_allows_under_limit(self, limiter):
        """Test requests allowed under limit."""
        # Should not raise for 5 requests (limit is 5)
        for _ in range(5):
            await limiter.check("test-plugin")

    @pytest.mark.asyncio
    async def test_check_rejects_over_limit(self, limiter):
        """Test requests rejected over limit."""
        # Use up the limit
        for _ in range(5):
            await limiter.check("test-plugin")

        # 6th request should be rejected
        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check("test-plugin")

        assert exc_info.value.retry_after_ms > 0
        assert "test-plugin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_window_expiry(self, limiter):
        """Test old requests expire from window."""
        # Use up the limit
        for _ in range(5):
            await limiter.check("test-plugin")

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Should be allowed again
        await limiter.check("test-plugin")

    @pytest.mark.asyncio
    async def test_check_plugins_independent(self, limiter):
        """Test plugins have independent limits."""
        # Use up limit for plugin A
        for _ in range(5):
            await limiter.check("plugin-a")

        # Plugin B should still be allowed
        await limiter.check("plugin-b")

        # Plugin A should be blocked
        with pytest.raises(RateLimitError):
            await limiter.check("plugin-a")

    @pytest.mark.asyncio
    async def test_check_custom_limit_applied(self, limiter):
        """Test custom limit is applied."""
        limiter.set_limit("high-priority", 10)

        # Should allow 10 requests for high-priority
        for _ in range(10):
            await limiter.check("high-priority")

        # 11th should fail
        with pytest.raises(RateLimitError):
            await limiter.check("high-priority")

    @pytest.mark.asyncio
    async def test_check_zero_limit_blocks_all(self, limiter):
        """Test zero limit blocks all requests."""
        limiter.set_limit("blocked", 0)

        with pytest.raises(RateLimitError):
            await limiter.check("blocked")

    # Check without record tests

    @pytest.mark.asyncio
    async def test_check_without_record_does_not_count(self, limiter):
        """Test check_without_record doesn't count against limit."""
        # Check 10 times without recording
        for _ in range(10):
            result = await limiter.check_without_record("test-plugin")
            assert result is True

        # Still should be able to use full limit
        for _ in range(5):
            await limiter.check("test-plugin")

    @pytest.mark.asyncio
    async def test_check_without_record_returns_false_over_limit(self, limiter):
        """Test check_without_record returns False when over limit."""
        # Use up limit
        for _ in range(5):
            await limiter.check("test-plugin")

        # Pre-flight check should return False
        result = await limiter.check_without_record("test-plugin")
        assert result is False

    # Status tests

    def test_get_status_empty(self, limiter):
        """Test status for plugin with no activity."""
        status = limiter.get_status("new-plugin")

        assert status.plugin == "new-plugin"
        assert status.limit == 5
        assert status.current == 0
        assert status.remaining == 5
        assert status.reset_at_ms is None

    @pytest.mark.asyncio
    async def test_get_status_after_requests(self, limiter):
        """Test status reflects request count."""
        await limiter.check("test-plugin")
        await limiter.check("test-plugin")

        status = limiter.get_status("test-plugin")

        assert status.current == 2
        assert status.remaining == 3
        assert status.reset_at_ms is not None

    @pytest.mark.asyncio
    async def test_get_all_status(self, limiter):
        """Test get_all_status returns all plugins."""
        await limiter.check("plugin-a")
        await limiter.check("plugin-b")
        await limiter.check("plugin-b")

        all_status = limiter.get_all_status()

        assert "plugin-a" in all_status
        assert "plugin-b" in all_status
        assert all_status["plugin-a"].current == 1
        assert all_status["plugin-b"].current == 2

    # Reset tests

    @pytest.mark.asyncio
    async def test_reset_single_plugin(self, limiter):
        """Test resetting single plugin."""
        for _ in range(5):
            await limiter.check("test-plugin")

        await limiter.reset("test-plugin")

        # Should be allowed again
        await limiter.check("test-plugin")

    @pytest.mark.asyncio
    async def test_reset_all_plugins(self, limiter):
        """Test resetting all plugins."""
        await limiter.check("plugin-a")
        await limiter.check("plugin-b")

        await limiter.reset()

        status_a = limiter.get_status("plugin-a")
        status_b = limiter.get_status("plugin-b")

        assert status_a.current == 0
        assert status_b.current == 0

    # Metrics tests

    @pytest.mark.asyncio
    async def test_get_metrics(self, limiter):
        """Test metrics collection."""
        await limiter.check("plugin-a")
        await limiter.check("plugin-a")
        await limiter.check("plugin-b")

        metrics = limiter.get_metrics()

        assert metrics["total_plugins"] == 2
        assert metrics["total_requests_tracked"] == 3
        assert metrics["default_limit"] == 5
        assert metrics["window_seconds"] == 1

    @pytest.mark.asyncio
    async def test_metrics_plugins_at_limit(self, limiter):
        """Test metrics shows plugins at limit."""
        # Fill up plugin-a (5/5 = 100% of limit)
        for _ in range(5):
            await limiter.check("plugin-a")

        metrics = limiter.get_metrics()

        assert metrics["plugins_at_limit"] >= 1

    # Concurrent access tests

    @pytest.mark.asyncio
    async def test_concurrent_checks(self):
        """Test concurrent checks are handled safely."""
        limiter = SQLRateLimiter(default_limit=100, window_seconds=60)

        # Run 100 concurrent checks
        async def check():
            await limiter.check("test-plugin")

        await asyncio.gather(*[check() for _ in range(100)])

        status = limiter.get_status("test-plugin")
        assert status.current == 100

    @pytest.mark.asyncio
    async def test_concurrent_checks_hit_limit(self):
        """Test concurrent checks properly hit limit."""
        limiter = SQLRateLimiter(default_limit=50, window_seconds=60)

        async def check():
            try:
                await limiter.check("test-plugin")
                return True
            except RateLimitError:
                return False

        # Run 100 concurrent checks with limit of 50
        results = await asyncio.gather(*[check() for _ in range(100)])

        # Should have exactly 50 successes
        assert sum(results) == 50

    # Retry-after calculation tests

    @pytest.mark.asyncio
    async def test_retry_after_calculation(self):
        """Test retry_after_ms is calculated correctly."""
        limiter = SQLRateLimiter(default_limit=1, window_seconds=2)

        # First request - allowed
        await limiter.check("test-plugin")

        # Second request - should fail with retry_after
        try:
            await limiter.check("test-plugin")
            pytest.fail("Should have raised RateLimitError")
        except RateLimitError as e:
            # retry_after should be close to window_seconds (2000ms)
            # Allow some tolerance for timing
            assert 1000 <= e.retry_after_ms <= 2000
