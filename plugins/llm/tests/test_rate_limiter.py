"""
Tests for LLM Rate Limiter
===========================

Tests for per-user rate limiting across multiple time windows.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from plugins.llm.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    UsageWindow,
    UserUsage,
)


@pytest.fixture
def rate_config():
    """Create test rate limit configuration."""
    return RateLimitConfig(
        requests_per_minute=5,
        requests_per_hour=20,
        requests_per_day=50,
        tokens_per_day=1000,
    )


@pytest.fixture
def rate_limiter(rate_config):
    """Create rate limiter with test config."""
    return RateLimiter(rate_config)


# ============================================================================
# Initialization Tests
# ============================================================================


@pytest.mark.asyncio
async def test_rate_limiter_init():
    """Test rate limiter initialization with defaults."""
    limiter = RateLimiter()
    
    assert limiter._config.requests_per_minute == 10
    assert limiter._config.requests_per_hour == 100
    assert limiter._config.requests_per_day == 500
    assert limiter._config.tokens_per_day == 50_000
    assert len(limiter._usage) == 0


@pytest.mark.asyncio
async def test_rate_limiter_init_with_config(rate_config):
    """Test rate limiter initialization with custom config."""
    limiter = RateLimiter(rate_config)
    
    assert limiter._config.requests_per_minute == 5
    assert limiter._config.requests_per_hour == 20
    assert limiter._config.requests_per_day == 50
    assert limiter._config.tokens_per_day == 1000


# ============================================================================
# Check Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_within_limits(rate_limiter):
    """Test check passes when within limits."""
    allowed, reason = await rate_limiter.check("user1")
    
    assert allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_check_minute_limit(rate_limiter):
    """Test minute limit enforcement."""
    # Record up to limit
    for i in range(5):
        allowed, _ = await rate_limiter.check("user1")
        assert allowed is True
        await rate_limiter.record("user1")
    
    # Next should fail
    allowed, reason = await rate_limiter.check("user1")
    assert allowed is False
    assert "minute" in reason.lower()
    assert "5" in reason


@pytest.mark.asyncio
async def test_check_hour_limit(rate_limiter):
    """Test hour limit enforcement."""
    # Fast-forward through minutes by resetting windows
    for i in range(20):
        allowed, _ = await rate_limiter.check("user1")
        assert allowed is True
        await rate_limiter.record("user1")
        
        # Reset minute window to simulate time passing
        rate_limiter._usage["user1"].minute.count = 0
    
    # Next should fail on hour limit
    allowed, reason = await rate_limiter.check("user1")
    assert allowed is False
    assert "hour" in reason.lower()


@pytest.mark.asyncio
async def test_check_day_limit_requests(rate_limiter):
    """Test day request limit enforcement."""
    # Fast-forward through minutes and hours
    for i in range(50):
        allowed, _ = await rate_limiter.check("user1")
        assert allowed is True
        await rate_limiter.record("user1")
        
        # Reset shorter windows
        rate_limiter._usage["user1"].minute.count = 0
        rate_limiter._usage["user1"].hour.count = 0
    
    # Next should fail on day limit
    allowed, reason = await rate_limiter.check("user1")
    assert allowed is False
    assert "day" in reason.lower()


@pytest.mark.asyncio
async def test_check_day_limit_tokens(rate_limiter):
    """Test day token limit enforcement."""
    # Record requests with tokens (990 tokens)
    for i in range(9):
        allowed, _ = await rate_limiter.check("user1")
        assert allowed is True
        await rate_limiter.record("user1", tokens_used=110)
        
        # Reset shorter windows
        rate_limiter._usage["user1"].minute.count = 0
        rate_limiter._usage["user1"].hour.count = 0
    
    # Should still pass (990 tokens used, limit is 1000)
    allowed, reason = await rate_limiter.check("user1")
    assert allowed is True
    
    # One more with 11 tokens should fail (total 1001)
    await rate_limiter.record("user1", tokens_used=11)
    allowed, reason = await rate_limiter.check("user1")
    assert allowed is False
    assert "token" in reason.lower()


@pytest.mark.asyncio
async def test_check_multiple_users(rate_limiter):
    """Test that users have independent limits."""
    # User1 hits minute limit
    for i in range(5):
        await rate_limiter.record("user1")
    
    # User1 blocked
    allowed, _ = await rate_limiter.check("user1")
    assert allowed is False
    
    # User2 still allowed
    allowed, _ = await rate_limiter.check("user2")
    assert allowed is True


# ============================================================================
# Record Tests
# ============================================================================


@pytest.mark.asyncio
async def test_record_basic(rate_limiter):
    """Test basic recording of requests."""
    await rate_limiter.record("user1")
    
    usage = await rate_limiter.get_usage("user1")
    assert usage["requests_minute"] == 1
    assert usage["requests_hour"] == 1
    assert usage["requests_day"] == 1
    assert usage["tokens_day"] == 0


@pytest.mark.asyncio
async def test_record_with_tokens(rate_limiter):
    """Test recording with token usage."""
    await rate_limiter.record("user1", tokens_used=100)
    
    usage = await rate_limiter.get_usage("user1")
    assert usage["requests_minute"] == 1
    assert usage["tokens_day"] == 100


@pytest.mark.asyncio
async def test_record_multiple_times(rate_limiter):
    """Test recording multiple requests."""
    for i in range(3):
        await rate_limiter.record("user1", tokens_used=50)
    
    usage = await rate_limiter.get_usage("user1")
    assert usage["requests_minute"] == 3
    assert usage["requests_hour"] == 3
    assert usage["requests_day"] == 3
    assert usage["tokens_day"] == 150


# ============================================================================
# Usage Tracking Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_usage_new_user(rate_limiter):
    """Test getting usage for new user."""
    usage = await rate_limiter.get_usage("newuser")
    
    assert usage["requests_minute"] == 0
    assert usage["requests_hour"] == 0
    assert usage["requests_day"] == 0
    assert usage["tokens_day"] == 0
    assert usage["limit_minute"] == 5
    assert usage["limit_hour"] == 20
    assert usage["limit_day"] == 50
    assert usage["limit_tokens_day"] == 1000


@pytest.mark.asyncio
async def test_get_remaining(rate_limiter):
    """Test getting remaining capacity."""
    # Record some usage
    for i in range(2):
        await rate_limiter.record("user1", tokens_used=100)
    
    remaining = await rate_limiter.get_remaining("user1")
    
    assert remaining["requests_minute"] == 3  # 5 - 2
    assert remaining["requests_hour"] == 18   # 20 - 2
    assert remaining["requests_day"] == 48    # 50 - 2
    assert remaining["tokens_day"] == 800     # 1000 - 200


# ============================================================================
# Window Reset Tests
# ============================================================================


@pytest.mark.asyncio
async def test_window_expiration():
    """Test that windows reset after expiration."""
    limiter = RateLimiter()
    
    # Record request
    await limiter.record("user1")
    
    # Manually expire the minute window
    usage = limiter._usage["user1"]
    usage.minute.reset_at = datetime.now() - timedelta(seconds=1)
    
    # Check should reset the window
    allowed, _ = await limiter.check("user1")
    assert allowed is True
    
    # Usage should be reset
    stats = await limiter.get_usage("user1")
    assert stats["requests_minute"] == 0
    assert stats["requests_hour"] == 1  # Hour not expired
    assert stats["requests_day"] == 1   # Day not expired


# ============================================================================
# Reset Tests
# ============================================================================


@pytest.mark.asyncio
async def test_reset_user(rate_limiter):
    """Test resetting user usage."""
    # Record some usage
    await rate_limiter.record("user1", tokens_used=100)
    await rate_limiter.record("user2", tokens_used=50)
    
    # Reset user1
    await rate_limiter.reset_user("user1")
    
    # User1 should be reset
    usage1 = await rate_limiter.get_usage("user1")
    assert usage1["requests_day"] == 0
    assert usage1["tokens_day"] == 0
    
    # User2 should be unchanged
    usage2 = await rate_limiter.get_usage("user2")
    assert usage2["requests_day"] == 1
    assert usage2["tokens_day"] == 50


# ============================================================================
# Threshold Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_threshold_not_exceeded(rate_limiter):
    """Test threshold check when under threshold."""
    await rate_limiter.record("user1")
    
    result = await rate_limiter.check_threshold("user1", 0.8)
    assert result is None


@pytest.mark.asyncio
async def test_check_threshold_exceeded(rate_limiter):
    """Test threshold check when threshold exceeded."""
    # Record 4 out of 5 minute requests (80%)
    for i in range(4):
        await rate_limiter.record("user1")
    
    result = await rate_limiter.check_threshold("user1", 0.8)
    
    assert result is not None
    window_type, current, limit = result
    assert window_type == "minute"
    assert current == 4
    assert limit == 5


@pytest.mark.asyncio
async def test_check_threshold_custom_percentage(rate_limiter):
    """Test threshold check with custom percentage."""
    # Record 2 out of 5 minute requests (40%)
    for i in range(2):
        await rate_limiter.record("user1")
    
    # 40% threshold
    result = await rate_limiter.check_threshold("user1", 0.4)
    assert result is not None
    
    # 50% threshold
    result = await rate_limiter.check_threshold("user1", 0.5)
    assert result is None


# ============================================================================
# Global Stats Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_global_stats(rate_limiter):
    """Test getting global statistics."""
    # Record usage for multiple users
    await rate_limiter.record("user1", tokens_used=100)
    await rate_limiter.record("user1", tokens_used=50)
    await rate_limiter.record("user2", tokens_used=200)
    
    stats = await rate_limiter.get_global_stats()
    
    assert stats["total_users"] == 2
    assert stats["total_requests_day"] == 3
    assert stats["total_tokens_day"] == 350


@pytest.mark.asyncio
async def test_get_global_stats_empty(rate_limiter):
    """Test global stats with no users."""
    stats = await rate_limiter.get_global_stats()
    
    assert stats["total_users"] == 0
    assert stats["total_requests_day"] == 0
    assert stats["total_tokens_day"] == 0


# ============================================================================
# Concurrency Tests
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_checks(rate_limiter):
    """Test concurrent checks from same user."""
    # Run concurrent checks
    results = await asyncio.gather(*[
        rate_limiter.check("user1")
        for _ in range(10)
    ])
    
    # All should pass (no recording yet)
    assert all(allowed for allowed, _ in results)


@pytest.mark.asyncio
async def test_concurrent_records(rate_limiter):
    """Test concurrent recording from same user."""
    # Run concurrent records
    await asyncio.gather(*[
        rate_limiter.record("user1")
        for _ in range(5)
    ])
    
    # All should be counted
    usage = await rate_limiter.get_usage("user1")
    assert usage["requests_minute"] == 5
    
    # Next check should fail
    allowed, _ = await rate_limiter.check("user1")
    assert allowed is False
