"""
SQL Rate Limiter for parameterized SQL queries.

This module provides rate limiting for SQL queries on a per-plugin basis
using a sliding window algorithm to enforce configurable quotas.

Example:
    >>> limiter = SQLRateLimiter(default_limit=100, window_seconds=60)
    >>> await limiter.check("my-plugin")  # OK
    >>> # After 100 queries in a minute...
    >>> await limiter.check("my-plugin")  # Raises RateLimitError
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

from .sql_errors import SQLValidationError


class RateLimitError(SQLValidationError):
    """
    Rate limit exceeded for SQL queries.

    Raised when a plugin exceeds its configured query quota. Includes
    retry_after_ms to indicate when the client can retry.

    Example:
        >>> try:
        ...     await limiter.check("my-plugin")
        ... except RateLimitError as e:
        ...     print(f"Retry after {e.retry_after_ms}ms")
    """

    def __init__(
        self,
        message: str,
        retry_after_ms: int,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Initialize rate limit error.

        Args:
            message: Human-readable error message
            retry_after_ms: Milliseconds until rate limit resets
            details: Optional additional context
        """
        self.retry_after_ms = retry_after_ms
        full_details = details or {}
        full_details["retry_after_ms"] = retry_after_ms
        super().__init__("RATE_LIMIT_EXCEEDED", message, full_details)


@dataclass
class RateLimitStatus:
    """
    Current rate limit status for a plugin.

    Attributes:
        plugin: Plugin name
        limit: Maximum queries allowed per window
        current: Number of queries used in current window
        remaining: Queries remaining before limit
        window_seconds: Size of rate limit window in seconds
        reset_at_ms: Timestamp when oldest request expires (Unix ms)
    """

    plugin: str
    limit: int
    current: int
    remaining: int
    window_seconds: int
    reset_at_ms: Optional[int] = None


class SQLRateLimiter:
    """
    Rate limiter for SQL queries using sliding window algorithm.

    Enforces per-plugin query quotas to prevent abuse and ensure fair
    resource sharing. Uses a sliding window to provide smooth rate limiting.

    Features:
        - Per-plugin configurable limits
        - Sliding window algorithm (no burst at window edges)
        - Async-safe with lock protection
        - Status introspection for monitoring

    Example:
        >>> limiter = SQLRateLimiter(default_limit=100, window_seconds=60)
        >>> limiter.set_limit("high-priority-plugin", 500)
        >>>
        >>> # In request handler:
        >>> await limiter.check("my-plugin")  # Raises if over limit
        >>> # ... execute query ...
        >>>
        >>> # Get status for monitoring:
        >>> status = limiter.get_status("my-plugin")
        >>> print(f"Remaining: {status.remaining}/{status.limit}")

    Thread Safety:
        All public methods are async-safe and can be called concurrently.
    """

    def __init__(
        self,
        default_limit: int = 100,
        window_seconds: int = 60,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            default_limit: Default queries per window for all plugins
            window_seconds: Size of sliding window in seconds
        """
        if default_limit <= 0:
            raise ValueError("default_limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._plugin_limits: dict[str, int] = {}
        self._windows: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    def set_limit(self, plugin: str, limit: int) -> None:
        """
        Set custom rate limit for a plugin.

        Args:
            plugin: Plugin name
            limit: Maximum queries per window (0 to block all)

        Raises:
            ValueError: If limit is negative
        """
        if limit < 0:
            raise ValueError("limit cannot be negative")
        self._plugin_limits[plugin] = limit

    def get_limit(self, plugin: str) -> int:
        """
        Get configured limit for a plugin.

        Args:
            plugin: Plugin name

        Returns:
            Configured limit (custom or default)
        """
        return self._plugin_limits.get(plugin, self.default_limit)

    def remove_limit(self, plugin: str) -> None:
        """
        Remove custom limit for a plugin (revert to default).

        Args:
            plugin: Plugin name
        """
        self._plugin_limits.pop(plugin, None)

    async def check(self, plugin: str) -> None:
        """
        Check if request is allowed under rate limit.

        Call this before executing a query. If allowed, the request is
        recorded in the window. If not allowed, raises RateLimitError.

        Args:
            plugin: Plugin name

        Raises:
            RateLimitError: If rate limit exceeded, includes retry_after_ms
        """
        async with self._lock:
            now = time.time()
            limit = self._plugin_limits.get(plugin, self.default_limit)

            # Get or create window
            if plugin not in self._windows:
                self._windows[plugin] = []

            window = self._windows[plugin]

            # Remove expired entries (outside sliding window)
            cutoff = now - self.window_seconds
            window[:] = [t for t in window if t > cutoff]

            # Check limit
            if len(window) >= limit:
                # Calculate when oldest request expires
                oldest = min(window) if window else now
                retry_after_ms = max(1, int((oldest + self.window_seconds - now) * 1000))
                raise RateLimitError(
                    f"Rate limit exceeded for '{plugin}': "
                    f"{limit} queries per {self.window_seconds}s",
                    retry_after_ms=retry_after_ms,
                    details={
                        "plugin": plugin,
                        "limit": limit,
                        "window_seconds": self.window_seconds,
                        "current": len(window),
                    },
                )

            # Record this request
            window.append(now)

    async def check_without_record(self, plugin: str) -> bool:
        """
        Check if a request would be allowed without recording it.

        Useful for pre-flight checks or monitoring.

        Args:
            plugin: Plugin name

        Returns:
            True if request would be allowed, False otherwise
        """
        async with self._lock:
            now = time.time()
            limit = self._plugin_limits.get(plugin, self.default_limit)

            if plugin not in self._windows:
                return True

            window = self._windows[plugin]
            cutoff = now - self.window_seconds
            current = sum(1 for t in window if t > cutoff)

            return current < limit

    def get_status(self, plugin: str) -> RateLimitStatus:
        """
        Get current rate limit status for a plugin.

        Args:
            plugin: Plugin name

        Returns:
            RateLimitStatus with current usage information
        """
        now = time.time()
        limit = self._plugin_limits.get(plugin, self.default_limit)
        window = self._windows.get(plugin, [])
        cutoff = now - self.window_seconds

        # Count current valid entries
        valid_times = [t for t in window if t > cutoff]
        current = len(valid_times)

        # Calculate reset time (when oldest entry expires)
        reset_at_ms = None
        if valid_times:
            oldest = min(valid_times)
            reset_at_ms = int((oldest + self.window_seconds) * 1000)

        return RateLimitStatus(
            plugin=plugin,
            limit=limit,
            current=current,
            remaining=max(0, limit - current),
            window_seconds=self.window_seconds,
            reset_at_ms=reset_at_ms,
        )

    def get_all_status(self) -> dict[str, RateLimitStatus]:
        """
        Get rate limit status for all tracked plugins.

        Returns:
            Dict mapping plugin names to their RateLimitStatus
        """
        return {plugin: self.get_status(plugin) for plugin in self._windows}

    async def reset(self, plugin: Optional[str] = None) -> None:
        """
        Reset rate limit window for a plugin or all plugins.

        Useful for testing or administrative override.

        Args:
            plugin: Plugin to reset, or None to reset all
        """
        async with self._lock:
            if plugin is None:
                self._windows.clear()
            else:
                self._windows.pop(plugin, None)

    def get_metrics(self) -> dict[str, Any]:
        """
        Get rate limiter metrics for monitoring.

        Returns:
            Dict with metrics including:
            - total_plugins: Number of plugins with activity
            - total_requests_tracked: Total requests in all windows
            - plugins_at_limit: Number of plugins at or near limit
        """
        now = time.time()
        cutoff = now - self.window_seconds

        total_requests = 0
        plugins_at_limit = 0

        for plugin, window in self._windows.items():
            valid_count = sum(1 for t in window if t > cutoff)
            total_requests += valid_count

            limit = self._plugin_limits.get(plugin, self.default_limit)
            if valid_count >= limit * 0.9:  # 90% of limit
                plugins_at_limit += 1

        return {
            "total_plugins": len(self._windows),
            "total_requests_tracked": total_requests,
            "plugins_at_limit": plugins_at_limit,
            "default_limit": self.default_limit,
            "window_seconds": self.window_seconds,
            "custom_limits": len(self._plugin_limits),
        }
